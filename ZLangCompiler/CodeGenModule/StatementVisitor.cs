using LLVMSharp.Interop;
using ParserModule;
using ParserModule.Nodes;

namespace CodeGenModule;

internal sealed class StatementVisitor : IStatementNodeVisitor
{
    private readonly LLVMContextRef _context;
    private readonly LLVMValueRef _func;
    private readonly LLVMBuilderRef _builder;
    private readonly Dictionary<string, LLVMValueRef> _scope;

    public StatementVisitor(LLVMContextRef context, LLVMBuilderRef builder, LLVMValueRef func, Dictionary<string, LLVMValueRef> scope)
    {
        _context = context;
        _builder = builder;
        _scope = scope;
        _func = func;
    }

    public void VisitVarAssignmentStatement(VarAssignmentStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitForStatement(ForStatemetNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitBlockStatement(BlockStatementNode node)
    {
        foreach (var statement in node.Statements)
        {
            statement.Accept(this);
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
            var expressionVisitor = new ExpressionVisitor(_scope, _builder);
            node.Result.Accept(expressionVisitor);
            _builder.BuildRet(expressionVisitor.Result);
        }
    }

    public void VisitStructImportStatementNode(StructImportStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitIfStatementNode(IfStatementNode node)
    {
        var expressionVisitor = new ExpressionVisitor(_scope, _builder);
        
        node.Condition.Accept(expressionVisitor);
        var condition = expressionVisitor.Result;

        var thenBlockRef = LLVMBasicBlockRef.AppendInContext(_context, _func, "then");
        var elseBlockRef = LLVMBasicBlockRef.AppendInContext(_context, _func, "else");

        _builder.BuildCondBr(condition, thenBlockRef, elseBlockRef);
    }
}