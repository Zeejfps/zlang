using ParserModule.Nodes;
using ParserModule.Nodes.Expressions;
using ParserModule.Visitors;

namespace SemanticAnalysisModule;

public sealed class SemanticTransformer : IAstNodeVisitor
{
    
    public void VisitFunctionDefinition(FunctionDefinitionNode node)
    {
        var isVoidFunction = node.Signature.ReturnType == null;
        
        node.Body.Accept(this);
        throw new NotImplementedException();
    }

    public void VisitStructDefinition(StructDefinitionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitExternFunctionDeclaration(ExternFunctionDeclarationNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitStructImport(ImportStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitModuleDefinition(ModuleDefinitionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitIfStatementNode(IfStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitBlockStatement(BlockStatementNode node)
    {
        
        throw new NotImplementedException();
    }

    public void VisitReturnStatementNode(ReturnStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitForStatement(ForStatemetNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitVarDeclaration(VarDeclarationStatementNode node)
    {

    }
    
    public void VisitVarAssignment(VarAssignmentStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitWhileStatement(WhileStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitExpressionStatement(ExpressionStatement node)
    {
        throw new NotImplementedException();
    }

    public void VisitBinary(BinaryExpressionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitUnary(UnaryExpressionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitLiteralInteger(LiteralIntegerExpressionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitLiteralBool(LiteralBoolExpressionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitQualifiedIdentifier(QualifiedIdentifierExpressionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitFunctionCall(FunctionCallNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitNamedType(NamedTypeNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitPtrType(PtrTypeNode node)
    {
        throw new NotImplementedException();
    }
}