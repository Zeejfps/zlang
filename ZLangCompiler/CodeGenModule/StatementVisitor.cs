using LLVMSharp.Interop;
using ParserModule;
using ParserModule.Nodes;

namespace CodeGenModule;

internal sealed class StatementVisitor : IStatementNodeVisitor
{
    private readonly LLVMBuilderRef _builder;
    private readonly Dictionary<string, LLVMValueRef> _scope;

    public StatementVisitor(LLVMBuilderRef builder, Dictionary<string, LLVMValueRef> scope)
    {
        _builder = builder;
        _scope = scope;
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
        // Console.WriteLine("VisitBlockStatement");
        // var block = _funcRef.AppendBasicBlock("entry");
        // _builder.PositionAtEnd(block);
        // foreach (var statement in node.Statements)
        // {
        //     statement.Accept(this);
        // }
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
        throw new NotImplementedException();
    }
}