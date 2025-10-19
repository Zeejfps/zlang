using LLVMSharp.Interop;
using ParserModule.Nodes;
using ParserModule.Visitors;

namespace CodeGenModule;

internal sealed class StatementVisitor : IStatementNodeVisitor
{
    private readonly LLVMContextRef _context;
    private readonly LLVMValueRef _func;
    private readonly LLVMTypeRef _funcType;
    private readonly LLVMBuilderRef _builder;
    private readonly Dictionary<string, LLVMValueRef> _scope;
    private readonly Dictionary<string, FunctionSymbol> _functions;

    public StatementVisitor(
        LLVMContextRef context,
        LLVMBuilderRef builder,
        LLVMValueRef func,
        LLVMTypeRef funcType,
        Dictionary<string, LLVMValueRef> scope,
        Dictionary<string, FunctionSymbol> functions)
    {
        _context = context;
        _builder = builder;
        _scope = scope;
        _functions = functions;
        _funcType = funcType;
        _func = func;
    }

    public void VisitVarDefinition(VarDefinitionStatementNode node)
    {
        var expressionVisitor = new ExpressionVisitor(_scope, _functions, _builder);
        node.Value.Accept(expressionVisitor);
        var value = expressionVisitor.Result;
        var allocaRef = _builder.BuildAlloca(value.TypeOf, node.Identifier);
        _builder.BuildStore(value, allocaRef);
        _scope.Add(node.Identifier, allocaRef);
    }

    public void VisitForStatement(ForStatemetNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitVarDeclaration(VarDeclarationStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitVarAssignment(VarAssignmentStatementNode node)
    {
        var expressionVisitor = new ExpressionVisitor(_scope, _functions, _builder);
        node.Value.Accept(expressionVisitor);
        _builder.BuildStore(expressionVisitor.Result, _scope[node.Name]);
    }

    public void VisitWhileStatement(WhileStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitExpressionStatement(ExpressionStatement node)
    {
        var expressionVisitor = new ExpressionVisitor(_scope, _functions, _builder);
        node.Expression.Accept(expressionVisitor);
    }

    public void VisitBlockStatement(BlockStatementNode node)
    {
        foreach (var statement in node.Statements)
        {
            statement.Accept(this);
        }

        if (_builder.InsertBlock.Terminator == default)
        {
            Console.WriteLine("Warning: Block statement has no terminator");
            _builder.BuildBr(_func.LastBasicBlock);
        }
    }
    
    public void VisitReturnStatementNode(ReturnStatementNode node)
    {
        if (node.Result == null)
        {
            _builder.BuildRetVoid();
        }
        else
        {
            var expressionVisitor = new ExpressionVisitor(_scope, _functions, _builder);
            node.Result.Accept(expressionVisitor);
            var resultValueRef = expressionVisitor.Result;
            if (resultValueRef.TypeOf.Kind != _funcType.ReturnType.Kind)
            {
                resultValueRef = _builder.BuildLoad2(_funcType.ReturnType, resultValueRef);
            }
            _builder.BuildRet(resultValueRef);
        }
    }

    public void VisitIfStatementNode(IfStatementNode node)
    {
        var expressionVisitor = new ExpressionVisitor(_scope, _functions, _builder);
        
        node.Condition.Accept(expressionVisitor);
        var condition = expressionVisitor.Result;

        var thenBlockRef = LLVMBasicBlockRef.AppendInContext(_context, _func, "then");
        var mergeBlockRef = LLVMBasicBlockRef.AppendInContext(_context, _func, "end");
        var elseBlockRef = mergeBlockRef;

        if (node.ElseBranch != null)
        {
            elseBlockRef = LLVMBasicBlockRef.AppendInContext(_context, _func, "else");
        }
        
        _builder.BuildCondBr(condition, thenBlockRef, elseBlockRef);
        
        _builder.PositionAtEnd(thenBlockRef);
        node.ThenBranch.Accept(this);

        if (node.ElseBranch != null)
        {
            _builder.PositionAtEnd(elseBlockRef);
            node.ElseBranch.Accept(this);   
        }

        _builder.PositionAtEnd(mergeBlockRef);
    }
}