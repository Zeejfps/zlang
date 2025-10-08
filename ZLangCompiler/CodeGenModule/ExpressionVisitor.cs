using LLVMSharp.Interop;
using ParserModule;
using ParserModule.Nodes;

namespace CodeGenModule;

public sealed class ExpressionVisitor : IAstNodeVisitor
{
    private readonly Dictionary<string, LLVMValueRef> _scope;

    public ExpressionVisitor(Dictionary<string, LLVMValueRef> scope)
    {
        _scope = scope;
    }

    public LLVMValueRef Value { get; private set; }
    
    public void VisitLiteralIntegerNode(LiteralIntegerNode node)
    {
        Value = LLVMValueRef.CreateConstInt(LLVMTypeRef.Int32, (ulong)node.Value);
    }

    public void VisitLiteralBoolNode(LiteralBoolNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitBinaryExpression(BinaryExpressionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitUnaryExpression(UnaryExpressionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitIdentifierNode(IdentifierNode node)
    {
        Value = _scope[node.Name];
    }

    public void VisitVarAssignmentStatement(VarAssignmentStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitNamedTypeNode(NamedTypeNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitBlockStatement(BlockStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitFunctionDeclarationNode(FunctionDefinitionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitReturnStatementNode(ReturnStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitParameterNode(ParameterNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitStructImportNode(StructImportNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitQualifiedIdentifierNode(QualifiedIdentifierNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitStructDefinitionNode(StructDefinitionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitModuleDefinitionNode(ModuleDefinitionNode node)
    {
        throw new NotImplementedException();
    }
}